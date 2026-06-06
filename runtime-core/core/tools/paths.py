from core.tools.files import get_cache_directory

def generate_source_reference(path, base=str(get_cache_directory())):
  if not path:
    return None
  path = str(path)
  return path.replace(
                base, '/uploads'
            )