# ExtractEnrich placeholder
import azure.functions as func

def main(msg: func.QueueMessage, toPost: func.Out[str]):
    toPost.set('{"vendor":"Adobe"}')
