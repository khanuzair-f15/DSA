class Solution(object):
    def removeDuplicates(self, nums):
        """
        :type nums: List[int]
        :rtype: int
        """
        x=set(nums)
        x=list(x)
        x=sorted(x)
        nums[:]=x
        return len(x)
