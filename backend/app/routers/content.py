# 构建pandoc命令
            pandoc_cmd = ['pandoc', '-f', 'markdown', '-t', 'docx', '-o', temp_docx_path, temp_md_path]

            # 查找参考文档模板
            ref_filename = None
            if reference_doc:
                ref_filename = reference_doc
            else:
                default_tpl = db.query(Template).filter(Template.is_default == True).first()
                if default_tpl:
                    ref_filename = default_tpl.filename

            if ref_filename:
                format_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'format')
                format_dir = os.path.abspath(format_dir)
                reference_path = os.path.join(format_dir, ref_filename)
                if os.path.exists(reference_path):
                    pandoc_cmd = ['pandoc', '--reference-doc', reference_path, '-f', 'markdown', '-t', 'docx', '-o', temp_docx_path, temp_md_path]
                else:
                    print(f"[export] 模板文件不存在: {reference_path}")

            result = subprocess.run(