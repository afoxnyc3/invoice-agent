# PostToAP placeholder
import azure.functions as func

def main(msg: func.QueueMessage, toNotify: func.Out[str]):
    toNotify.set('{"title":"Invoice submitted"}')
