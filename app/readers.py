
def read_vocab(vocab_file):
    c = 0
    vocab = {}
    reverse_vocab = {}
    logprobs = []
    with open(vocab_file) as f:
        for l in f:
            l = l.rstrip('\n')
            wp = l.split('\t')[0]
            logprob = -(float(l.split('\t')[1]))
            #logprob = log(lp + 1.1)
            if wp in vocab or wp == '':
                continue
            vocab[wp] = c
            reverse_vocab[c] = wp
            logprobs.append(logprob)
            c+=1
    return vocab, reverse_vocab, logprobs

def read_cosines(cosine_file):
    cosines = {}
    with open(cosine_file) as f:
        for l in f:
            l = l.rstrip('\n')
            fields = l.split()
            wp = fields[0]
            cosines[wp] = fields[2:]
    return cosines

