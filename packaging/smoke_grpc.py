"""对打包后的 backend.exe 做一次真实 gRPC 冒烟调用。

用法：
    python packaging/smoke_grpc.py <port>

验证三件事：
    1) 打包后的 exe 能拉起 gRPC 服务（而不是只有命令行参数能跑）；
    2) GetStatus 有真实返回（后端引擎确实初始化了）；
    3) ListPlugins 能列出内置插件（datas 收进去了，不是空壳）。
"""
import os
import sys

import grpc

PORT = sys.argv[1] if len(sys.argv) > 1 else '50051'
TARGET = f'127.0.0.1:{PORT}'

# xiaoling_pb2_grpc.py 是老版本 protoc 生成的，里面写的是顶层
# `import xiaoling_pb2`，必须把 backend/rpc 本身也放进 sys.path 才导得进来。
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..'))
_RPC = os.path.join(_ROOT, 'backend', 'rpc')
sys.path.insert(0, _ROOT)
sys.path.insert(0, _RPC)

try:
    from backend.rpc import xiaoling_pb2 as pb
    from backend.rpc import xiaoling_pb2_grpc as pbg
except ImportError:
    print('导入失败：请在仓库根目录运行，并保证已安装 grpcio')
    raise SystemExit(2)

ok = True
with grpc.insecure_channel(TARGET) as ch:
    grpc.channel_ready_future(ch).result(timeout=40)
    stub = pbg.XiaoLingStub(ch)

    st = stub.GetStatus(pb.StatusRequest(), timeout=30)
    print('[GetStatus] ok=%s stage=%s model=%s backend=%s version=%s'
          % (st.ok, st.stage, st.model, st.backend, st.version))
    if not st.model:
        ok = False
        print('  !! model 为空，怀疑资源目录没打包进去')

    pl = stub.ListPlugins(pb.Empty(), timeout=30)
    names = [p.name for p in pl.plugins]
    print('[ListPlugins] 共 %d 个：%s' % (len(names), '、'.join(names[:12])))
    if not names:
        ok = False
        print('  !! 一个插件都没有，说明 .star_core/plugins 的 plugin.json 没带进包')

print('=== 冒烟结果：%s ===' % ('通过' if ok else '失败'))
raise SystemExit(0 if ok else 1)
