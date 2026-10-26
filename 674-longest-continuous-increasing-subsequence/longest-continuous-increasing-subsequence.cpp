class Solution {
public:
    int findLengthOfLCIS(vector<int>& nums) {
        int maxlen = 1;
        int count = 1;
        for (int i = 0; i < nums.size() - 1; i++) {
            if (nums[i] < nums[i + 1]) {
                count++;
            } else {
                count = 1;
            }
            maxlen = max(maxlen, count);
        }
        return maxlen;
    }
};