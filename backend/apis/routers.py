from fastapi import APIRouter
from core.conf import settings
from apis.v1.platform import router as platform_router
from apis.v1.platform_strategy import router as indicators_strategy_router
from apis.v1.platform_trade import router as trade_strategy
from apis.v1.game import router as game_strategy
from apis.v1.websocket_forward import router as websocket_forward



v1 = APIRouter(prefix=settings.API_V1_STR)

v1.include_router(platform_router, prefix='/platform', tags=['平台-K线-指标'])
v1.include_router(indicators_strategy_router, prefix='/platform/strategy', tags=['策略'])
v1.include_router(trade_strategy, prefix='/platform/trade', tags=['交易策略'])
v1.include_router(game_strategy, prefix='/game', tags=['英雄排行'])
v1.include_router(websocket_forward, prefix='/platform/forward', tags=['请求转发'])