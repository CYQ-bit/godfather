# Godfather 统一自动启动框架

## 未来版本接入规范

### 规则 1: 内部逻辑升级 - 不新增服务
如果新版本只是现有主链内部升级（例如 V10.0 / V10.1 / V10.5）：
- **不新增 launchd 服务**
- 继续使用所属版本服务（PT44 / V91）
- 只更新代码，不动自动启动框架

### 规则 2: 独立版本 - 新增服务配置
如果新版本是独立运行根目录 + 独立账户 + 独立调度脚本：

1. 创建服务配置文件：
```bash
${GODFATHER_ROOT}/config/services/v100.json
```

2. 配置文件格式：
```json
{
  "service_name": "v100",
  "label": "com.cyq.godfather.v100",
  "root_dir": "${GODFATHER_ROOT}_v100",
  "entry_script": "${GODFATHER_ROOT}_v100/scripts/run_godfather_v100.sh",
  "stdout_log": "${GODFATHER_ROOT}/logs/v100_stdout.log",
  "stderr_log": "${GODFATHER_ROOT}/logs/v100_stderr.log",
  "run_at_load": true,
  "keep_alive": false,
  "enabled": true
}
```

3. 执行同步和启动：
```bash
cd ${GODFATHER_ROOT}
python3 scripts/godfather_service_manager.py sync
python3 scripts/godfather_service_manager.py bootstrap
```

### 命名规范
所有未来版本统一遵循：`com.cyq.godfather.<service_name>`

## 一键命令

```bash
# 生成 plist + 启动所有服务
bash ${GODFATHER_ROOT}/scripts/bootstrap_godfather_all.sh

# 重启所有服务
bash ${GODFATHER_ROOT}/scripts/restart_godfather_all.sh

# 检查状态
bash ${GODFATHER_ROOT}/scripts/check_godfather_status.sh
```
