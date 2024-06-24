import joblib
from glob import glob
from os.path import join, dirname, realpath
from app import models
    
dir_path = dirname(dirname(realpath(__file__)))
pod_dir = getenv("PODS_DIR", join(dir_path, 'pods'))

def load_posix(contributor, lang, theme):
    posix_path = join(dir_path, 'pods', contributor, lang)
    pod_name = theme+'.u.'+contributor
    posix = joblib.load(join(posix_path,pod_name+'.pos'))
    return posix

def dump_posix(posindex, contributor, lang, theme):
    posix_path = join(dir_path, 'pods', contributor, lang)
    pod_name = theme+'.u.'+contributor
    joblib.dump(posindex, join(posix_path,pod_name+'.pos'))

def posix_doc(text, doc_id, contributor, lang, theme):
    pod_name = theme+'.u.'+contributor
    posindex = load_posix(contributor, lang, theme)
    vocab = models[lang]['vocab']
    for pos, token in enumerate(text.split()):
        if token not in vocab:
            # tqdm.write(f"WARNING: token \"{token}\" not found in vocab")
            continue
        token_id = vocab[token]
        if doc_id in posindex[token_id]:
            posindex[token_id][doc_id] += f"|{pos}"
        else:
            posindex[token_id][doc_id] = f"{pos}"
    dump_posix(posindex, contributor, lang, theme)

def get_pod_sizes(pod_paths, lang):
    pod_sizes = {}
    for path in pod_paths:
        filename = path.split('/')[-1]
        theme, contributor = filename.replace('.pos','').split('.u.')
        _, idx = joblib.load(join(pod_dir, contributor, lang, theme+'.u.'+contributor+'.npz.idx'))
        pod_sizes[filename] = len(idx)
    pod_sizes = dict(sorted(pod_sizes.items(), key=lambda item: item[1], reverse=True))
    return pod_sizes

def load_posindices(lang, n = -1):
    pod_paths = glob(join(pod_dir,'*',lang,'*.u.*pos'))
    posindices = {}
    if n == -1:
        for path in pod_paths:
            filename = path.split('/')[-1]
            theme, contributor = filename.replace('.pos','').split('.u.')
            posindices[theme] = load_posix(contributor, lang, theme)
    else:
        pod_sizes = get_pod_sizes(pod_paths, lang)
        n_pod_names = dict(list(pod_sizes.items())[:n])
        for filename, size in n_pod_names.items():
            theme, contributor = filename.replace('.pos','').split('.u.')
            print("Loading pod", theme, contributor, size)
            posindices[theme] = load_posix(contributor, lang, theme)
    return posindices
