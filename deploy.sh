#!/bin/bash
# AI 写作助手 — 服务部署管理脚本
# 通过 screen 持久化管理服务，SSH 断开后继续运行
# 用法: ./deploy.sh {start|stop|status|restart|logs}

SERVICES=("extraction" "p2p-proxy" "backend")
BASE_DIR="/home/liubin/writing-assistant"
KNG_DIR="/home/liubin/kng-dev/kng-dev"
PYTHON="/home/liubin/miniconda3/envs/writing/bin/uvicorn"
P2P="/home/liubin/kng-dev/kng-dev/p2p-proxy"

BACKEND_PORT=9000
FRONTEND_PORT=7500

start_service() {
    case "$1" in
        extraction)
            screen -dmS extraction bash -c "cd $BASE_DIR/doc-extraction-server && $PYTHON app.extractor_main:app --host 0.0.0.0 --port 8050"
            echo "  [extraction] 端口 8050 — 公文字段提取服务"
            ;;
        p2p-proxy)
            screen -dmS p2p-proxy bash -c "$P2P '85af8f' '85af8f2c-a929-bca0-80a6-c9599a227430' '127.0.0.1:8050'"
            echo "  [p2p-proxy] 公网地址: https://85af8f.xhang.buaa.edu.cn:52811"
            ;;
        backend)
            screen -dmS backend bash -c "cd $BASE_DIR/backend && BACKEND_PORT=$BACKEND_PORT KNG_BASE_URL=http://127.0.0.1:50001 $PYTHON app.main:app --host 0.0.0.0 --port $BACKEND_PORT"
            echo "  [backend] 端口 $BACKEND_PORT — 写作助手后端"
            ;;
        frontend)
            screen -dmS frontend bash -c "cd $BASE_DIR/frontend && FRONTEND_PORT=$FRONTEND_PORT npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT"
            echo "  [frontend] 端口 $FRONTEND_PORT — 写作助手前端"
            ;;
        *)
            echo "  未知服务: $1"
            ;;
    esac
}

stop_service() {
    screen -S "$1" -X quit 2>/dev/null
    echo "  [$1] 已停止"
}

status_service() {
    if screen -ls 2>/dev/null | grep -q "$1"; then
        echo "  [$1] ✅ 运行中"
        return 0
    else
        echo "  [$1] ❌ 未运行"
        return 1
    fi
}

logs_service() {
    screen -r "$1"
}

case "$1" in
    start)
        echo "🔵 启动所有服务..."
        for s in "${SERVICES[@]}"; do
            start_service "$s"
        done
        echo "✅ 全部启动完成"
        echo "   查看状态: ./deploy.sh status"
        echo "   查看日志: ./deploy.sh logs <服务名>"
        ;;
    stop)
        echo "🔴 停止所有服务..."
        for s in extraction p2p-proxy backend frontend; do
            stop_service "$s"
        done
        echo "✅ 全部已停止"
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        echo "📊 服务运行状态:"
        for s in extraction p2p-proxy backend frontend; do
            status_service "$s"
        done
        echo ""
        echo "📡 端口监听:"
        ss -tlnp 2>/dev/null | grep -E "8050|${BACKEND_PORT}|50001|${FRONTEND_PORT}"
        ;;
    logs)
        if [ -z "$2" ]; then
            echo "用法: ./deploy.sh logs {extraction|p2p-proxy|backend|frontend}"
            exit 1
        fi
        logs_service "$2"
        ;;
    *)
        echo "AI 写作助手 — 服务管理脚本"
        echo ""
        echo "用法:"
        echo "  ./deploy.sh start             启动所有服务"
        echo "  ./deploy.sh stop              停止所有服务"
        echo "  ./deploy.sh restart           重启所有服务"
        echo "  ./deploy.sh status            查看运行状态"
        echo "  ./deploy.sh logs <服务名>      查看日志（Ctrl+A+D 退出）"
        echo ""
        echo "服务列表:"
        echo "  extraction   公文字段提取服务   :8050"
        echo "  p2p-proxy    公网穿透          https://85af8f.xhang.buaa.edu.cn:52811"
        echo "  backend      写作助手后端       :${BACKEND_PORT}"
        echo "  frontend     写作助手前端       :${FRONTEND_PORT}"
        ;;
esac