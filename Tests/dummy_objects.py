from collections import deque

from pymget import *


class CallChecker:
    def __getattribute__(self, name):
        try:
            attr = object.__getattribute__(self, name)
        except:
            if name.endswith('_called'):
                return False
            raise
        if callable(attr):
            setattr(self, name + '_called', True)
        return attr



class DummyProgressBar(CallChecker, console.IProgressBar):

    def __init__(self, total, old_progress):
        pass

    def update(self, complete):
        pass


class DummyConsole(CallChecker, console.IConsole):

    text = None

    def create_progressbar(self, total, old_progress):
        pass

    def message(self, text='', end='\n'):
        self.text = text

    def error(self, text, end='\n'):
        self.text = text

    def warning(self, text, end='\n'):
        self.text = text

    def ask(self, text, default):
        self.text = text
        return False

    def progress(self, complete):
        self.progress_value = complete

    @property
    def _progressbar(self):
        return DummyProgressBar


class DummyContext(CallChecker, outfile.IContext):

    def __init__(self, filename):
        self.clean = True
        self.offset = 0
        self.written_bytes = 0
        self.failed_parts = []

    def open_context(self):
        pass

    def update(self, offset, written_bytes, failed_parts):
        pass

    def reset(self):
        self.clean = True

    def delete(self):
        pass



class DummyURL:

    def __init__(self, url):
        self.url = url
        self.protocol = 'protocol'
        self.host = 'host'
        self.request = 'request'
        self.path = 'path'
        self.filename = 'filename'



import queue

class DummyDataQueue(CallChecker, data_queue.IDataQueue):

    def __init__(self):
        self.objects = deque([])

    def put(self, obj):
        self.objects.append(obj)

    def get(self, block=False, timeout=0):
        try:
            return self.objects.popleft()
        except:
            raise queue.Empty


class DummyHTTXConnection:

    response = None

    def request(self, method, request, headers):
        self.request = request
        self.headers = headers

    def getresponse(self):
        return self.response

    def __call__(self, host, timeout):
        return self

    def close(self):
        pass


class DummyHTTXResponse:

    def __init__(self, status, headers, data=b''):
        self.i = 0
        self.status = status
        self.data = data
        self.headers = headers

    def getheader(self, name):
        return self.headers[name]

    def close(self):
        pass

    def read(self, size):
        self.i += size
        return self.data[self.i - size:self.i]


class DummyFTPConnection:

    socket = None

    def __init__(self, host, login, password, timeout):
        pass

    def voidcmd(self, cmd):
        pass

    def cwd(self, path):
        pass

    def size(self, filename):
        return 100

    def transfercmd(self, filename, offset):
        return self.socket

    def close(self):
        pass


class DummySocket:

    def __init__(self, data=b''):
        self.i = 0
        self.data = data

    def recv(self, size):
        self.i += size
        return self.data[self.i - size:self.i]

    def close(self):
        pass



class DummyEvent:

    def wait(self, timeout):
        return True

class DummyThread(CallChecker, networking.INetworkThread):

    def __init__(self):
        self.ready = DummyEvent()

    def start(self):
        self.start_called = True

    def join(self):
        self.join_called = True

    def cancel(self):
        self.cancel_called = True

class DummyConnectionThread(DummyThread):

    def __init__(self, url, timeout):
        DummyThread.__init__(self)
        self.conn = None

class DummyDownloadThread(DummyThread):

    def __init__(self, url, conn, offset, block_size, filesize=0):
        DummyThread.__init__(self)



class DummyMirror(CallChecker, mirrors.IMirror):

    @classmethod
    def create(cls, url, block_size, timeout):
        return cls(url, block_size, timeout)

    def __init__(self, url, block_size, timeout):
        self.filename = 'filename'
        self.block_size = block_size
        self.url = url
        self.ready = False
        self.need_connect = False
        self.task_progress = 0
        self.name = 'name'

    def wait_connection(self):
        return True

    def connect(self):
        pass

    def download(self, offset):
        self.offset = offset

    def cancel(self):
        pass

    def join(self):
        pass

    def close(self):
        pass

    def done(self):
        pass

    def connect_message(self, text):
        pass


class DummyCommandLine(CallChecker, command_line.ICommandLine):

    def __init__(self, console, argv):
        self.block_size = 10
        self.filename = ''
        self.timeout = 0
        self.urls = []

    def parse(self):
        pass

class DummyOutputFile(CallChecker, outfile.IOutputFile):

    def __init__(self, console, user_path):
        self.user_path = user_path
        self.context = DummyContext('')
        self.filename = 'filename'

    def __enter__(self):
        return self 

    def __exit__(self, exception_type, exception_value, traceback):
        pass

    def create_path(self, user_path):
        pass

    def seek(self, offset):
        pass

    def write(self, data):
        pass


class DummyTaskInfo(CallChecker, task_info.ITaskInfo):

    def process(self, manager):
        pass


class DummyManager(CallChecker, manager.IManager):

    def __init__(self):
        pass

    def prepare(self, console, command_line, outfile):
        pass

    def download(self):
        pass

    def del_active_part(self, offset):
        pass

    def add_failed_part(self, offset):
        pass

    def delete_mirror(self, name):
        pass

    def set_file_size(self, task_info):
        pass

    def redirect(self, task_info):
        pass

    def do_error(self, task_info):
        pass

    def set_progress(self, task_info):
        pass

    def write_data(self, task_info):
        pass
