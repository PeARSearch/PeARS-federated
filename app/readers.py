
def read_vocab(vocab_file):
    c = 0
    vocab = {}
    reverse_vocab = {}
    logprobs = []
    with open(vocab_file, encoding='utf-8') as f:
        for l in f:
            l = l.rstrip('\n').strip()  # Remove any trailing newline and extra spaces
            vocab_list = l.rsplit(maxsplit=1)
            if len(vocab_list) < 2:
                print("Couldn't split the line:", l)
                continue
            wp = vocab_list[0]
            logprob = -(float(vocab_list[1]))
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

