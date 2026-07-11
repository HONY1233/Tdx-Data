# AKShare MCP Server

基于 [AKShare](https://github.com/akfamily/akshare) + [AxData](https://github.com/electkismet/AxData) 的金融数据 MCP 服务器，整合两个数据源，提供 A股、指数、ETF、期货、外围指数、涨跌停、龙虎榜、期权、新闻等金融数据查询。

## 功能特性

- **36 个 MCP 工具**，覆盖 A股/指数/ETF/期货/期权/新闻等全品类金融数据
- **双数据源整合**：akshare + axdata，自动路由到最佳来源
- **统一数据查询接口** `data_query`：31 个统一别名，一个入口查询所有数据
- **多源 fallback**：东方财富 push2 不可用时自动 fallback 到新浪
- **自动参数转换**：新浪/TDX 代码格式互转，参数名映射
- **三种部署模式**：stdio（IDE集成）、SSE、streamable-http

## 数据源

| 数据源 | 覆盖范围 |
|--------|----------|
| **新浪财经** | A股日线/实时、指数、ETF、期货、美股/港股指数、龙虎榜、期权 |
| **东方财富** | 涨停池/跌停池、板块行情、大盘指数、ETF 实时 |
| **财联社** | 电报快讯、市场情绪、涨停池、板块热度、今日风口、今日主线 |
| **开盘红** | 市场情绪（真实涨停、ST涨跌） |
| **巨潮信息网** | 公告、公司概况、财务摘要、分红配送 |
| **腾讯财经** | A股历史日线 |

## 工具列表（36 个）

### 统一接口（2 个）
- `data_query` - 统一数据查询接口，支持 31 个别名
- `data_interfaces` - 列出所有可用接口

### A股行情（4 个）
- `stock_zh_a_daily` - A股个股日线历史（前复权）
- `stock_zh_index_daily` - A股指数日线历史
- `stock_zh_index_spot` - A股指数实时行情
- `stock_zh_a_spot` - A股个股实时行情

### 财经新闻（4 个）
- `cls_telegraph` - 财联社电报（支持关键词/级别/标红/时间过滤）
- `news_cctv` - 新闻联播文字稿
- `news_economic_calendar` - 财经日历
- `stock_news` - 个股新闻

### 巨潮信息（4 个）
- `stock_notice_cninfo` - 上市公司公告
- `stock_profile_cninfo` - 公司基本资料
- `stock_financial_abstract_cninfo` - 财务摘要
- `stock_dividend_cninfo` - 分红配送

### 期货（3 个）
- `futures_realtime` - 期货实时行情
- `futures_daily` - 期货历史日线
- `futures_global_spot` - 全球期货实时行情

### 外围指数（3 个）
- `index_us_daily` - 美股指数日线（道琼斯/纳斯达克/标普500）
- `index_hk_daily` - 港股指数日线（恒生/国企/恒生科技）
- `index_global_list` - 全球指数代码表

### ETF（2 个）
- `fund_etf_spot` - ETF 实时行情列表
- `fund_etf_daily` - ETF 历史日线

### AxData 专用工具（14 个）
- `stock_limit_up_pool` - 涨停池（含涨停原因、连板数、主力资金）
- `stock_limit_down_pool` - 跌停池
- `sector_realtime` - 板块实时行情
- `market_emotion_cls` - 财联社市场情绪
- `market_emotion_kph` - 开盘红市场情绪
- `cls_limit_up_pool` - 财联社涨停池
- `cls_sector_heat` - 财联社板块热度
- `cls_market_wind` - 财联社今日风口
- `cls_market_mainline` - 财联社今日主线
- `stock_lhb_daily` - 龙虎榜每日详情
- `stock_lhb_institution` - 龙虎榜机构席位
- `futures_main_display` - 期货主力合约展示
- `option_commodity_list` - 商品期权品种
- `option_cffex_hs300_list` - 沪深300期权合约

## 安装

```bash
pip install -r requirements.txt
```

依赖：
- `akshare>=1.18.0` - 金融数据
- `fastmcp>=3.0.0` - MCP 框架
- `pandas>=2.0.0` - 数据处理
- `curl_cffi>=0.7.0` - HTTP 客户端
- `axdata>=0.1.0` - AxData 数据源

## 运行

### 方式一：启动脚本

```bash
cd akshare-mcp
./run.sh                # stdio 模式（默认，IDE集成）
./run.sh sse            # SSE 模式，0.0.0.0:8000
./run.sh sse 9000       # SSE 模式，端口 9000
./run.sh http 8080      # streamable-http 模式
./run.sh list           # 列出所有可用工具
```

### 方式二：直接运行

```bash
python3 server.py                          # stdio 模式
python3 server.py -t sse                   # SSE 模式
python3 server.py -t sse --port 9000       # SSE 模式，自定义端口
python3 server.py -t streamable-http       # HTTP 模式
python3 server.py --list                  # 列出工具
```

## MCP 配置

### Trae IDE / Claude Desktop / Cursor

在 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "akshare": {
      "command": "python3",
      "args": ["/path/to/akshare-mcp/server.py"],
      "env": {}
    }
  }
}
```

### SSE 远程连接

服务端启动：
```bash
./run.sh sse 8000
```

客户端配置：
```json
{
  "mcpServers": {
    "akshare": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

## 使用示例

### 统一查询接口

```python
# 查询个股日线（支持多种代码格式）
data_query(interface="stock_daily", params_json='{"symbol": "000936"}', limit=5)

# 查询涨停池
data_query(interface="limit_up_pool", limit=10)

# 查询财联社市场情绪
data_query(interface="cls_market_emotion")

# 查询期货日线
data_query(interface="futures_daily", params_json='{"symbol": "V0"}', limit=5)

# 查看所有可用接口
data_interfaces()
```

### 专用工具

```python
# 财联社电报（标红新闻，最近1小时）
cls_telegraph(limit=20, red_only=True, hours=1)

# 涨停池
stock_limit_up_pool(limit=50)

# A股实时行情（多只）
stock_zh_a_spot(symbols="000936,600519")
```

## 项目结构

```
akshare-mcp/
├── server.py             # 主服务（36个工具 + 统一调用层）
├── cls_telegraph.py      # 财联社电报独立脚本
├── run.sh                # 启动脚本
├── mcp.json              # MCP 配置示例
├── requirements.txt      # 依赖列表
├── pyproject.toml        # 项目打包配置
├── Dockerfile            # Docker 容器配置
├── docker-compose.yml    # Docker Compose 配置
└── README.md
```

## 免责声明

数据来自第三方公开接口，可能存在延迟、缺失或错误，仅供技术研究与学习使用，不构成投资建议。
