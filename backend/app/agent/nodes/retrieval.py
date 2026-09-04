from __future__ import annotations

from .common import *

def create_plan_retrieval_node(context: AgentExecutionContext):
    async def plan_retrieval(state: WritingState):
        async def operation():
            if not state.get("use_kng"):
                return {}
            prompt = (
                "你负责为中文公文写作规划知识库检索。根据文种、用户完整要求和写作 Skill，"
                "自行判断需要几个相互独立的检索任务；简单事项不要机械拆分，多个独立事项可以分别查询，"
                "相近主题必须合并。不得使用任何预设主题。每条 query 必须可以独立发送给知识库，"
                "并写明要寻找的制度依据、事实或既有做法，以及需要排除的无关方向。"
                f"单次运行最多允许 {MAX_KNG_QUERIES} 个查询。\n\n"
                f"文种：{state['document_type']}\n"
                f"用户要求：{state.get('requirements', '')}\n\n"
                f"写作规划：{_draft_plan_text(state)}\n\n"
                f"材料使用方案：{_reference_strategy_text(state)}\n\n"
                f"Skill：\n{_skill_text(state, 'outline')}"
            )
            warnings = list(state.get("warnings") or [])
            try:
                plan = await context.model.complete_structured(
                    [{"role": "user", "content": prompt}], RetrievalPlan
                )
                tasks = _normalize_tasks(plan)
                if len(tasks) > MAX_KNG_QUERIES:
                    merge_prompt = (
                        f"以下检索计划超过 {MAX_KNG_QUERIES} 次调用预算。合并语义相近的查询，"
                        "保留所有独立事实需求，只返回合并后的计划；不得简单截断。\n\n"
                        f"原计划：{json.dumps(tasks, ensure_ascii=False)}"
                    )
                    merged = await context.model.complete_structured(
                        [{"role": "user", "content": merge_prompt}], RetrievalPlan
                    )
                    tasks = _normalize_tasks(merged)
                if not tasks or len(tasks) > MAX_KNG_QUERIES:
                    raise ValueError("模型未能生成预算内的有效检索计划")
                return {"retrieval_plan": tasks, "warnings": warnings}
            except Exception:
                warning = {
                    "code": "kng_planning_unavailable",
                    "message": "知识库检索规划不可用，已改为仅依据用户要求生成",
                }
                warnings.append(warning)
                await context.emit("warning", warning, "retrieval_plan")
                return {"retrieval_plan": [], "warnings": warnings}

        return await _stage(context, "retrieval_plan", state, operation)
    return plan_retrieval

def create_retrieve_node(context: AgentExecutionContext):
    async def retrieve(state: WritingState):
        async def operation():
            tasks = list(state.get("retrieval_plan") or [])
            if not tasks or not (state.get("use_kng") or state.get("use_web_search")):
                return {"raw_retrievals": []}
            service = get_kng_rag_service() if state.get("use_kng") else None
            warnings = list(state.get("warnings") or [])
            semaphore = asyncio.Semaphore(KNG_QUERY_CONCURRENCY)

            async def run_query(index: int, task: dict[str, Any]):
                async with semaphore:
                    context.check_cancelled()
                    backend = task.get("backend", "kng")
                    use_kng = bool(state.get("use_kng")) and backend in {"kng", "both"}
                    use_web = bool(state.get("use_web_search")) and backend in {"web", "both"}
                    if not use_kng and not use_web:
                        return {
                            "query_index": index, "task": task, "content": "",
                            "references": [], "error": "该查询后端未启用",
                        }
                    try:
                        if use_kng:
                            result = await asyncio.to_thread(
                                service.retrieve_for_document_generation,
                                topic=task["query"],
                                requirements="",
                                mode="hybrid",
                            )
                            content = str(result.get("content") or "")[:12000]
                            references = list(result.get("references") or [])
                        else:
                            results = await asyncio.to_thread(search_web, task["query"], max_results=5)
                            content = "\n\n".join(
                                f"{row['title']}：{row['excerpt']}"
                                for row in results
                            )[:12000]
                            references = [
                                f"{row['title']}（{row['url']}）"
                                for row in results
                            ]
                            result = {"content": content, "references": references}
                    except Exception as exc:
                        result = {"content": "", "references": [], "error": str(exc)}
                    return {
                        "query_index": index,
                        "task": task,
                        "content": str(result.get("content") or "")[:12000],
                        "references": list(result.get("references") or []),
                        "error": result.get("error"),
                        "backend": backend,
                    }

            kng_tasks = [item for item in tasks if item.get("backend", "kng") in {"kng", "both"}]
            web_tasks = [item for item in tasks if item.get("backend", "kng") in {"web", "both"}]
            if len(kng_tasks) > MAX_KNG_QUERIES:
                kng_tasks = kng_tasks[:MAX_KNG_QUERIES]
                warning = {"code": "kng_query_budget", "message": f"知识库查询已限制在 {MAX_KNG_QUERIES} 次"}
                warnings.append(warning)
                await context.emit("warning", warning, "retrieval")
            if len(web_tasks) > MAX_WEB_QUERIES:
                web_tasks = web_tasks[:MAX_WEB_QUERIES]
                warning = {"code": "web_query_budget", "message": f"联网查询已限制在 {MAX_WEB_QUERIES} 次"}
                warnings.append(warning)
                await context.emit("warning", warning, "retrieval")
            selected_tasks = kng_tasks + [item for item in web_tasks if item not in kng_tasks]
            raw_retrievals = await asyncio.gather(
                *(run_query(index, task) for index, task in enumerate(selected_tasks))
            )
            failed_count = sum(
                1 for item in raw_retrievals if item.get("error") or not item.get("content")
            )
            if not any(item.get("content") for item in raw_retrievals):
                warning = {
                    "code": "kng_unavailable" if state.get("use_kng") and not state.get("use_web_search") else "retrieval_unavailable",
                    "message": "检索服务当前不可用，已改为仅依据用户要求和上传材料生成",
                }
                warnings.append(warning)
                await context.emit("warning", warning, "retrieval")
            elif failed_count:
                warning = {
                    "code": "retrieval_partial_failure",
                    "message": f"有 {failed_count} 个检索任务未返回结果，已继续使用其余材料",
                }
                warnings.append(warning)
                await context.emit("warning", warning, "retrieval")
            return {"raw_retrievals": raw_retrievals, "warnings": warnings}

        return await _stage(context, "retrieval", state, operation)
    return retrieve

def create_filter_evidence_node(context: AgentExecutionContext):
    async def filter_evidence(state: WritingState):
        async def operation():
            raw_retrievals = [item for item in (state.get("raw_retrievals") or []) if item.get("content")]
            warnings = list(state.get("warnings") or [])
            existing_evidence = list(state.get("evidence") or [])
            existing_references = list(state.get("references") or [])
            if not raw_retrievals:
                if state["document_type"] == "regulation":
                    warning = {
                        "code": "regulation_basis_unverified",
                        "message": "制度依据未经知识库核验",
                    }
                    warnings.append(warning)
                    await context.emit("warning", warning, "evidence_filter")
                return {
                    "evidence": existing_evidence,
                    "references": existing_references,
                    "warnings": warnings,
                }

            filter_payload = [
                {
                    "query_index": item["query_index"],
                    "purpose": item["task"].get("purpose", ""),
                    "query": item["task"].get("query", ""),
                    "content": item["content"],
                    "references": item["references"],
                }
                for item in raw_retrievals
            ]
            prompt = (
                "筛选下列检索返回，形成可供公文起草使用的证据。必须逐项判断与用户任务的相关性。"
                "direct 可保留材料明确陈述的相关事实；partial 只能抽取相关句；irrelevant 不得输出。"
                "每条输出必须填写所属 query_index，并绑定该查询实际列出的一个或多个来源；"
                "不得根据来源标题补写材料没有陈述的内容；来源标题与该条检索任务明显无关时不得绑定，"
                "即使知识库汇总声称其有关也必须丢弃。\n\n"
                f"{KNG_USAGE_RULES}\n\n"
                f"文种：{state['document_type']}\n用户要求：{state.get('requirements', '')}\n\n"
                f"检索原始返回：{json.dumps(filter_payload, ensure_ascii=False)}"
            )
            try:
                filtered = await context.model.complete_structured(
                    [{"role": "user", "content": prompt}], EvidenceFilterResult
                )
            except Exception:
                warning = {
                    "code": "kng_filter_unavailable",
                    "message": "知识库结果无法完成相关性过滤，原始结果未用于正文",
                }
                warnings.append(warning)
                await context.emit("warning", warning, "evidence_filter")
                return {
                    "evidence": existing_evidence,
                    "references": existing_references,
                    "warnings": warnings,
                }

            raw_by_index = {item["query_index"]: item for item in raw_retrievals}
            accepted_evidence = []
            accepted_references = []
            seen_evidence = set()
            seen_references = {_normalize_text(item).casefold() for item in existing_references if isinstance(item, str)}
            for item in filtered.items:
                raw = raw_by_index.get(item.query_index)
                content = _normalize_text(item.content)
                if not raw or not content:
                    continue
                resolved_sources = []
                for candidate in item.source_refs:
                    resolved = _resolve_reference(candidate, raw.get("references") or [])
                    if (
                        resolved
                        and _reference_matches_task(resolved, raw.get("task") or {})
                        and resolved not in resolved_sources
                    ):
                        resolved_sources.append(resolved)
                if not resolved_sources:
                    continue
                evidence_key = content.casefold()
                if evidence_key in seen_evidence:
                    continue
                seen_evidence.add(evidence_key)
                accepted_evidence.append({
                    "kind": "web_evidence" if raw.get("backend") == "web" else "kng_evidence",
                    "query_index": item.query_index,
                    "relevance": item.relevance,
                    "content": content,
                    "sources": resolved_sources,
                })
                for reference in resolved_sources:
                    reference_key = _normalize_text(reference).casefold()
                    if reference_key not in seen_references:
                        seen_references.add(reference_key)
                        accepted_references.append(reference)

            if not accepted_evidence:
                warning = {
                    "code": "kng_no_relevant_evidence",
                    "message": "知识库未返回与当前任务直接相关的可用证据",
                }
                warnings.append(warning)
                await context.emit("warning", warning, "evidence_filter")
                if state["document_type"] == "regulation":
                    basis_warning = {
                        "code": "regulation_basis_unverified",
                        "message": "制度依据未经知识库核验",
                    }
                    warnings.append(basis_warning)
                    await context.emit("warning", basis_warning, "evidence_filter")
            for reference in accepted_references:
                source_kind = "web_result" if "http" in str(reference) and "（" in str(reference) else "kng_result"
                payload_reference = (
                    {"name": reference, "kind": source_kind}
                    if source_kind == "web_result" else reference
                )
                await context.emit("source.added", {"reference": payload_reference}, "evidence_filter")
            return {
                "evidence": [*existing_evidence, *accepted_evidence],
                "references": [*existing_references, *accepted_references],
                "warnings": warnings,
            }

        return await _stage(context, "evidence_filter", state, operation)
    return filter_evidence

__all__ = ['create_plan_retrieval_node', 'create_retrieve_node', 'create_filter_evidence_node']
