'''
    Run this with:
      uvicorn main:_app --host 0.0.0.0 --port 8000 --reload
'''
import threading
import app.utils as utils
from app import _app


logger = utils.get_app_logger()
logger.info('**iPerf network performance orchestrator started**')



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(_app, host="0.0.0.0", port=8000)
