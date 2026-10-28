class Solution {
public:
    int minimumSwaps(vector<int>& nums) {
        int i = 0;
        int j = nums.size() - 1;
        int count = 0;
        while (i < j) {
            if (nums[j] == 0) {
                j--;
            } else if (nums[i] != 0) {
                i++;
            } else if (nums[i] == 0 && nums[j] != 0) {
                swap(nums[i], nums[j]);
                count++;
                i++;
                j--;
            } else {
               // i++;
               // j--;
            }
        }
        return count;
    }
};