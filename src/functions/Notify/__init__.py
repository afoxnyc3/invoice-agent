# Notify placeholder
import azure.functions as func

def main(msg: func.QueueMessage):
    print('Notify: ', msg.get_body())
