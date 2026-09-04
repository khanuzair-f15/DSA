class Solution(object):
    def mergeAlternately(self, word1, word2):
        """
        :type word1: str
        :type word2: str
        :rtype: str
        """
        a=list(word1)
        b=list(word2)
        c=[]

        m=min(len(a),len(b))
        ma=max(len(a),len(b))
        for i in range(m):
            c.append(a[i])
        
            c.append(b[i])
        
        if len(a) > len(b):
            c.extend(a[m:])
        else:
            c.extend(b[m:])
        d="".join(c)
        return d