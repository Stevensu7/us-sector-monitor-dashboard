# US Sector Dashboard

一个本地运行的美股板块看板，展示：

- 各板块 ETF 在自定义时间区间内的涨跌幅
- 基于 OHLCV 的资金净流入/流出代理指标
- 日均成交额、最新量比和价格轨迹

## 运行方式

```bash
pip install -r requirements.txt
python app.py
```

浏览器打开本机启动后输出的地址即可。

## 直接打开 HTML 版本

如果你想双击直接打开，不启动 Python：

- 打开 `sector_dashboard_standalone.html`
- 确保 `sector_data.js` 和 `sector_dashboard_standalone.html` 在同一目录
- 这个版本直接读取本地内嵌历史数据，不依赖在线接口
- 如果你想更新到最新数据，重新运行：`python build_embedded_data.py`

## GitHub Pages

- 线上静态部署入口使用 `index.html`
- 本项目已适配直接部署到 GitHub Pages

## 数据说明

- 数据源：`yfinance`
- 板块映射：使用美股常用 Sector SPDR ETF
- 资金流向：使用 Chaikin Money Flow 思路，根据价格与成交量估算的公开数据代理值
- 这个指标适合看相对冷热和板块轮动，不等同于 ETF 官方申赎数据或交易所披露的真实资金流
