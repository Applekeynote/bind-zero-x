"""Bounded, expiring per-account jobs; no background queue beyond active slots."""
import secrets,threading,time

class PackingJobs:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.lock=threading.Lock();self.jobs={}
    def submit(self,owner,work,release):
        with self.lock:
            self.jobs={key:value for key,value in self.jobs.items() if self.clock()-value['created']<600 or value['status']=='PENDING'}
            if len(self.jobs)>=8:
                finished=[key for key,value in self.jobs.items() if value['status']!='PENDING']
                if not finished:raise RuntimeError('SEGMENTATION_CAPACITY_REACHED')
                del self.jobs[min(finished,key=lambda key:self.jobs[key]['created'])]
            key=secrets.token_urlsafe(24);self.jobs[key]={'owner':owner,'created':self.clock(),'status':'PENDING'}
        def run():
            try:
                result=work()
                with self.lock:self.jobs[key].update(status='DONE',result=result)
            except Exception as error:
                code=str(error)
                if code not in {'SEGMENTATION_MODEL_NOT_READY','SEGMENTATION_BUSY','NO_RELIABLE_INSTANCE_PROPOSALS','PNG_REQUIRED_UP_TO_5_MB','IMAGE_DIMENSIONS_OUT_OF_RANGE','INVALID_PNG'}:code='SEGMENTATION_FAILED'
                with self.lock:self.jobs[key].update(status='FAILED',error=code)
            finally:release()
        threading.Thread(target=run,daemon=True).start()
        return {'job_id':key,'status':'PENDING'}
    def read(self,key,owner):
        with self.lock:
            job=self.jobs.get(key)
            if not job or job['owner']!=owner or self.clock()-job['created']>=600:return None
            return {k:v for k,v in job.items() if k not in {'owner','created'}}
