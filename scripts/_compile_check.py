import py_compile, sys
files = [
    r'c:\Users\aakan\Documents\Projects\HostingPlatform\models\container.py',
    r'c:\Users\aakan\Documents\Projects\HostingPlatform\services\container_manager.py',
    r'c:\Users\aakan\Documents\Projects\HostingPlatform\scripts\ensure_docker_schema.py'
]
ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print('Compiled OK:', f)
    except Exception as e:
        ok = False
        print('Compile error in', f, e)
if not ok:
    sys.exit(1)
