class Solution(object):
    def isPalindrome(self, s):
        """
        :type s: str
        :rtype: bool
        """

        y = ""

        for ch in s:
            if ch.isalnum():
                y += ch

        x=y[::-1]
        if x.lower()==y.lower():
            return True
        else:
            return False