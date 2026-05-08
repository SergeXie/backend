

class OrderPoint():
    def __init__(self):
        self.orderpoint_list = []
        self.order_is_closed_list = []
        self.orde_id_list = []

    def get_last_list(self):
        if len(self.orderpoint_list) == 0:
            return None
        else:
            return self.orderpoint_list[-1]

    def add(self, datatime=None, order_type=None, price=None, size=None, orderId=None,
            **kwargs):
        self.orderpoint_list.append({'datatime': datatime,
                                    'order_type': order_type,
                                    'price': price,
                                    'size': size,
                                    'orderId': orderId})