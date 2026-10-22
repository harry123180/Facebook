"""Flask 擴充套件實例。

集中宣告避免循環 import：models 與 api 都從這裡拿 db。
"""

from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
