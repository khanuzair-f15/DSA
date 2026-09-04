class Solution(object):
    def canConstruct(self, ransomNote, magazine):
        """
        :type ransomNote: str
        :type magazine: str
        :rtype: bool
        """
        flag=0
        a=list(ransomNote)
        b=list(magazine)
        for i in range(len(a)):

            if a[i] not in b:
                flag=1
            else:
                b.remove(a[i])
                
        if flag==1:
            return False
        else:
            return True