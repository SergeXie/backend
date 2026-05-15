# ComprehensiveAnalyzer 统计公式说明

本文档整理两个综合统计类的字段口径：

- `core/bt/base/public_strategy.py` 中的 `ComprehensiveAnalyzer`
- `core/bt/tools/trader_report_calculate.py` 中的 `ManualComprehensiveAnalyzer`

两个类最终都返回同样的三组结构：

```json
{
  "overall": {},
  "long": {},
  "short": {}
}
```

- `overall`：多单和空单合并后的统计。
- `long`：多单统计。
- `short`：空单统计。

## 数据分组

### ComprehensiveAnalyzer

来源：Backtrader 已平仓 `trade` 对象。

- 多单：`trade.history[0].event.size > 0`
- 空单：`trade.history[0].event.size <= 0`
- 只统计 `trade.isclosed == True` 的交易。

### ManualComprehensiveAnalyzer

来源：接口/报告里的 `traderResult: list[dict]`。

- 多单：`placeType == "buy"`
- 空单：`placeType == "sell"`
- 未识别方向的数据不进入多空统计，也不会进入 `overall`。
- 每笔交易使用 `pnl` 作为盈亏。
- 持仓周期 `barlen` 由 `openTime`、`closeTime` 和 `period` 推算。

## 基础变量

以下公式里的 `trades` 表示当前分组的交易列表。

| 变量 | 公式 | 说明 |
| --- | --- | --- |
| `total_pnl` | `sum(pnl)` | 净利润 |
| `gross_profit` | `sum(pnl for pnl > 0)` | 总盈利 |
| `gross_loss` | `sum(pnl for pnl <= 0)` | 总亏损，代码中保留负数，持平单也计入亏损侧 |
| `count_total` | `len(trades)` | 总交易笔数 |
| `count_won` | `count(pnl > 0)` | 盈利笔数 |
| `count_lost` | `count(pnl <= 0)` | 亏损/持平笔数 |
| `avg_won` | `gross_profit / count_won` | 平均盈利 |
| `avg_lost` | `gross_loss / count_lost` | 平均亏损，通常为负数或 0 |
| `max_pnl` | `max(pnl)` | 单笔最大盈利 |
| `max_lost` | `min(pnl)` | 单笔最大亏损，通常为负数 |

## 返回字段公式

| 字段 | 公式 | 说明 |
| --- | --- | --- |
| `totalPnl` | `total_pnl` | 净利润 |
| `grossProfit` | `gross_profit` | 总盈利 |
| `grossLoss` | `gross_loss` | 总亏损，负数口径 |
| `profitLossRatio` | `gross_profit / -gross_loss` | 盈亏比。无亏损时返回 0 |
| `countTotal` | `count_total` | 总交易笔数 |
| `profitRatio` | `gross_profit / -gross_loss` | 当前代码和 `profitLossRatio` 同口径，不是胜率 |
| `countWon` | `count_won` | 盈利笔数 |
| `countLost` | `count_lost` | 亏损/持平笔数 |
| `avgCount` | 见下方说明 | 持平笔数 |
| `avgProfitRatio` | `avg_won / -avg_lost` | 平均盈利 / 平均亏损绝对值 |
| `avgWon` | `avg_won` | 平均盈利 |
| `avgLost` | `avg_lost` | 平均亏损，负数口径 |
| `avgProfitLossRatio` | `avg_won / (avg_won + -avg_lost)` | 平均盈利占平均盈亏总幅度的比例 |
| `maxPnl` | `max_pnl` | 单笔最大盈利 |
| `maxLost` | `max_lost` | 单笔最大亏损 |
| `maxProfitRatio` | `max_pnl / gross_profit` | 单笔最大盈利占总盈利比例 |
| `maxLossRatio` | `max_lost / gross_loss` | 单笔最大亏损占总亏损比例。两者通常都是负数，所以结果通常为正 |
| `netProfitLossRatio` | `total_pnl / max_lost` | 净利润 / 单笔最大亏损。最大亏损为负数时，正收益会得到负值 |
| `maxConsecutiveWins` | 最大连续 `pnl > 0` 数量 | 最大连续盈利笔数 |
| `maxConsecutiveLosses` | 最大连续 `pnl <= 0` 数量 | 最大连续亏损/持平笔数 |
| `avgLoldingPeriod` | `sum(barlen) / count_total` | 平均持仓周期，字段名源码拼写为 `Lolding` |
| `avgProfitPeriod` | 见下方说明 | 平均盈利持仓周期 |
| `avgLossPeriod` | 见下方说明 | 平均亏损持仓周期 |
| `avgBreakevenPeriod` | 见下方说明 | 平均持平持仓周期 |
| `maxEquity` | `self.max_equity` | 最大资金/权益 |
| `maxPositionSize` | `self.max_position_size` | 最大持仓数量 |
| `totalCosts` | `total_commission + total_slippage` | 成本合计 |
| `analysis` | `total_pnl / max_equity` | 收益率口径 |
| `annualizedReturn` | `0` | 当前未计算 |
| `EffectiveYield` | `0` | 当前未计算 |
| `AverageProfitMonth` | `0` | 当前未计算 |

## 周期字段差异

### ComprehensiveAnalyzer 当前实际返回

源码中：

```python
avg_profit_period = sum(trade.barlen for trade in trades if trade.pnl > 0)
if avg_profit_period:
    avg_profit_period / len([trade for trade in trades if trade.pnl > 0])
```

这里除法结果没有重新赋值，所以实际返回：

- `avgProfitPeriod`：盈利交易的 `barlen` 总和，不是平均值。
- `avgLossPeriod`：亏损/持平交易的 `barlen` 总和，不是平均值。
- `avgBreakevenPeriod`：固定返回 `0`。
- `avgCount`：固定返回 `0`。

如果业务期望是真正平均值，需要改成：

```python
avg_profit_period = total_profit_period / count_won if count_won else 0
avg_loss_period = total_loss_period / count_lost if count_lost else 0
```

### ManualComprehensiveAnalyzer 当前实际返回

该类周期计算更完整：

| 字段 | 公式 |
| --- | --- |
| `avgProfitPeriod` | `sum(barlen for pnl > 0) / count_won` |
| `avgLossPeriod` | `sum(barlen for pnl <= 0) / count_lost` |
| `avgBreakevenPeriod` | `sum(barlen for pnl == 0) / count(pnl == 0)` |
| `avgCount` | `count(pnl == 0)` |

## ManualComprehensiveAnalyzer 的 barlen 计算

```text
barlen = (closeTime - openTime 的分钟数) / period_minutes
```

周期换算：

| period | 分钟数 |
| --- | --- |
| `M1/M5/M15/M30` | 字母 `M` 后面的数字 |
| `H1` | `60` |
| `H4` | `240` |
| `D1` | `1440` |
| `W1` | `10080` |
| `MN` | `0`，当前不计算月线 bar 数 |

如果缺少 `openTime` 或 `closeTime`，或周期无法换算，`barlen = 0`。

## 精度

### ComprehensiveAnalyzer

精度来自第一组数据的 `digits`：

```python
digits = self.datas[0].digits[0]
precision_format = f".{int(digits)}f"
```

所有数值字段使用 `float(format(value, precision_format))` 格式化。

### ManualComprehensiveAnalyzer

固定使用：

```python
precision_format = ".3f"
```

即保留 3 位小数后再转回 `float`。

## 需要注意的口径问题

1. `gross_loss` 是负数，不是亏损绝对值。
2. `pnl == 0` 被计入亏损侧：`countLost`、连续亏损、平均亏损周期都会包含持平单。
3. `profitRatio` 当前不是胜率，而是 `gross_profit / -gross_loss`，和 `profitLossRatio` 一样。
4. `netProfitLossRatio = total_pnl / max_lost`，由于 `max_lost` 通常为负数，盈利策略可能返回负值。
5. `ComprehensiveAnalyzer` 的 `avgProfitPeriod`、`avgLossPeriod` 当前代码实际是总周期，不是平均周期。
6. `ManualComprehensiveAnalyzer` 只根据 `placeType` 分多空；如果数据只有 `orderType` 而没有 `placeType`，会被忽略。
