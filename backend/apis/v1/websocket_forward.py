from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
import asyncio
import websockets
from fastapi import APIRouter
import urllib.parse
import json
import httpx

import requests
from concurrent.futures import ThreadPoolExecutor
router = APIRouter()


async def websocket_message_processing(websocket: WebSocket, message: str):
    # if message != "ping":
    if 'method' in message:
        # print(message)
        message_data = json.loads(message)  # 转为字典
        response = await generate_request(message_data)  ###############################################问题所在
        if response.status_code == 200:
            # print('有response 系统错误!',response.status_code == 500, response.text)
            response_dict = json.loads(response.text)
            # print(type(response_dict))
            # print(response_dict)
            response_dict['json_data'] = message
            json_response = json.dumps(response_dict, ensure_ascii=False)  # 转为字符串
            # json_response = json.dumps(response, ensure_ascii=False)  # 转为字符串
            json_response = "HTTP_Response:" + json_response
            # print('json_response', json_response)
            await websocket.send(json_response)
        else:
            response_dict = {"status_code": response.status_code,
                             "text": response.text,
                             "json_data": message,
                             "Error": response.text}
            # print('response_dict有问题', response_dict)
            json_response = json.dumps(response_dict, ensure_ascii=False)  # 转为字符串
            await websocket.send(json_response)



async def websocket_background_task():
    uri = "ws://192.168.0.73:8000/api/v1/platform/wss"
    # uri = "ws://8.138.95.62:8000/api/v1/platform/wss"
    print("发起请求")
    while True:
        try:
            async with websockets.connect(uri) as ws:
                print(f"Connected to {uri}")
                # 这里可以添加逻辑来处理从服务器接收的消息
                while True:
                    message = await ws.recv()
                    print(f"Received message from server: {message}")
                    await websocket_message_processing(ws, message)

        except WebSocketDisconnect as e:
            print(f'发生WebSocketDisconnect错误: {e}')
            await asyncio.sleep(5)
            # await websocket_background_task()
        except websockets.ConnectionClosed as e:
            print(f'发生ConnectionClosed: {e}')
            await asyncio.sleep(5)
            # await websocket_background_task()
        except ConnectionRefusedError:
            # 当连接被拒绝时执行的代码
            print("连接被拒绝，5秒后重试。")
            await asyncio.sleep(5)
            # await websocket_background_task()



        # except (WebSocketDisconnect, websockets.ConnectionClosed, Exception) as e:
        #     print(f'连接断开或发生错误: {e}')
        #     # 如果连接断开或发生错误，等待一段时间后重试
        #     await asyncio.sleep(5)


# 整理长连接收到的字符串，并获取请求所需的url和参数
async def generate_request(data):

    # 提取字典中的各个部分
    path = data['path']
    query_params = data['query_params']
    headers = data['headers']

    # 构建查询字符串
    query_string = urllib.parse.urlencode(query_params)

    # 内网服务器的IP地址和端口
    INTERNAL_SERVER_IP = "192.168.0.73"
    INTERNAL_SERVER_PORT = "8081"

    # 构建完整的URL
    url = f"http://{INTERNAL_SERVER_IP}:{INTERNAL_SERVER_PORT}/{path}"
    method = data['method']
    print('method', data, method)
    print('####' * 3)

    if method == 'GET':
        response = await send_request('GET', url, headers=data['headers'], params=data['query_params'])
    elif method == 'POST':
        response = await send_request('POST', url, headers=data['headers'], data=data['body'])
    else:
        raise ValueError("Unsupported HTTP method")
    # print('有response', response)
    return response

# 发送模拟请求
async def send_request(method, url, headers=None, params=None, data=None):
    print(url)
    timeout = httpx.Timeout(5.0, read=300)
    if method.upper() == 'GET':
        print('GET转发', url)
        async with httpx.AsyncClient() as client:
            response = await client.get(url=url, params=params, timeout=timeout)
        # response = await requests.get(url, headers=headers, params=params)
    elif method.upper() == 'POST':
        print('POST转发')
        async with httpx.AsyncClient() as client:
            response = await client.post(url=url, json=json.loads(data), timeout=timeout)
        # response = await requests.post(url, headers=headers, json=json.loads(data))
    else:
        raise ValueError("Unsupported HTTP method")
    # print('有response', response.text)

    return response

# 全局标志变量，确保 startup 事件只执行一次
_startup_completed = False
@router.on_event("startup")
async def startup_event():
    global _startup_completed
    if not _startup_completed:
        print("启动事件执行")
        asyncio.create_task(websocket_background_task())
        _startup_completed = True
    else:
        print("启动事件已执行，跳过")