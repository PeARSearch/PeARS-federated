import joblib
from os.path import join, dirname, realpath
from app import models
    
dir_path = dirname(dirname(realpath(__file__)))

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
