# AKShare MCP Server

基于 [AKShare](https://github.com/akfamily/akshare) 的金融数据 MCP 服务器，提供A股、指数等行情数据查询。

## 功能

- `stock_zh_a_daily` - A股个股日线历史行情（前复权，新浪财经）
- `stock_zh_index_daily` - A股指数日线历史行情（新浪财经）
- `stock_zh_index_spot` - A股指数实时行情列表
- `stock_zh_a_spot` - A股个股实时行情

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python3 server.py
```

## MCP 配置

在 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "akshare": {
      "command": "python3",
      "args": ["/workspace/akshare-mcp/server.py"]
    }
  }
}
```

## 免责声明

数据来自第三方公开接口，可能存在延迟、缺失或错误，仅供技术研究与学习使用，不构成投资建议。
