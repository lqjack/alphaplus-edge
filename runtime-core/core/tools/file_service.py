from storage.models import Account, Article
import os
import io
from api.main import db, app
import time
from core.tools.times import time_to_timestamp
from datetime import datetime
from core.tools.files import get_cache_directory, encode_directory_name, get_upload_folder

def sync_file(folder_name=None, file=None, file_name=None, user='my'):
    if not folder_name:
        date = datetime.now().strftime("%Y%m%d")
        # 构建目录路径
        folder_name = os.path.join(get_cache_directory(), user, date)
    os.makedirs(folder_name, exist_ok=True)
    folder_name_str = encode_directory_name(folder_name)
    # 创建文件组Account
    with app.app_context():
        from api.main import db
        with db.session.no_autoflush:
            account = Account.query.filter_by(account_name=folder_name_str).first()
        if not account:
            account = Account(
                account_name=folder_name_str,
                account_desc=folder_name_str,
                account_url = folder_name,
                platform='file'
            )
            db.session.add(account)
            db.session.commit()
        
        Account.sync_account(account_id=account.id)
        save_path = os.path.join(get_upload_folder(), folder_name_str)
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
        if file:
            file_name = os.path.basename(file_name)
            file_path = os.path.join(save_path, file_name)
            if isinstance(file, io.BufferedReader):
                with open(file_path, 'wb') as f:
                    f.write(file.read()) 
            elif isinstance(file, bytes):
                with open(file_path, 'wb') as f:
                    f.write(file)
            else:
                file.save(file_path)
            from core.tools.files import get_file_content_type
            content_type = get_file_content_type(file_name)

            if not content_type:
                return None, 'failed'
        
            article = Article(
                article_title=file_name,
                article_content_url=file_path,
                article_author = user,
                article_publish_time=time_to_timestamp(time.time()),
                content_type=content_type,
                article_source_url=file_path,
                account_id=account.id
            )
            article.article_done = True
            db.session.add(article)
            db.session.commit()

        count = Article.query.filter_by(account_id=account.id).count()
        account = Account.get_account(account.id)
        now = datetime.utcnow()
        account.update = str(now)
        account.counts = count
        db.session.commit()
        if file:
            return article.id, 'article'
        else:
            return account.id, 'account'
        