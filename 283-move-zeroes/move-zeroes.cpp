class Solution {
public:
    void moveZeroes(vector<int>& nums) {
        int i = 0;
        int j = 0;
        /*
        0 1 0 3 12
        1 0 0 3 12
        1 3 0 0 12
        */
        while (i < nums.size() && j < nums.size()) {
            if (nums[i] == 0 && nums[j] == 0) {
                j++;
            } else if (nums[i] == 0 && nums[j] != 0) {
                swap(nums[i], nums[j]);
                j = i;
            } else if (nums[i] != 0 && nums[j] != 0) {
                i++;
                j++;
            }
        }
    }
};