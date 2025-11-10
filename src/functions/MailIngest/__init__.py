# MailIngest function placeholder
import azure.functions as func

def main(timer: func.TimerRequest, outQueueItem: func.Out[str]):
    outQueueItem.set('{"message_id":"1","subject":"Invoice Example"}')
