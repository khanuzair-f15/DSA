class Solution {
public:
    void moveZeroes(vector<int>& nums) {
        int n = 0, len = nums.size();

        for (int i = 0; i < len; i++) {
            if (nums[i] != 0)
                swap(nums[i], nums[n++]);
        }
    }
};