def split_and_sort_probability(data):
    tmp1 = sorted([p for p in data if p < 0])
    tmp2 = sorted([p for p in data if p > 0], reverse=True)
    return tmp1, tmp2