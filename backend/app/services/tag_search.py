from ..adapters.danbooru_sqlite import DanbooruSQLiteAdapter
from ..storage.repository import DATA
class TagService:
    def __init__(self,repo):
        self.repo=repo;self.active=None
        from ..storage.repository import Repository
        self.overrides=Repository(repo.path.parent/'user-tags.sqlite')
    def snapshot(self):
        if self.active is None:
            config=self.repo.get('settings',{}).get('tag_config',{}).get('tag_provider',{})
            self.active=DanbooruSQLiteAdapter(config.get('db_path') if config.get('enabled',True) else None,DATA,self.overrides.get('tag_overrides',{}))
        return self.active
    def configure(self,config,overrides=None):
        path=config.get('db_path') if config.get('enabled',True) else None;candidate=DanbooruSQLiteAdapter(path,DATA,overrides if overrides is not None else self.overrides.get('tag_overrides',{}))
        status=candidate.inspect_capabilities()
        if path and not status['available']:raise ValueError(status['error'])
        if config.get('verify_release_hash') and config.get('expected_sha256')!=status['snapshot_sha256']:raise ValueError('Release SHA-256이 일치하지 않습니다.')
        # Atomically switch the adapter only after complete schema/index verification.
        self.active=candidate;return status
