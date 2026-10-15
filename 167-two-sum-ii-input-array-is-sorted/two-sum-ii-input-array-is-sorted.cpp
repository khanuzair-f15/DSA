class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {

        int i = 0;
        int j = nums.size() - 1;
        // 2 7 11 15
        //
        while (i < j) {
            int sum = nums[i] + nums[j];
            if (sum == target) {
                return {i + 1, j + 1};
            } else if (sum > target) {
                j--;
            } else {
                i++;
            }
        }
        return {};
    }
};