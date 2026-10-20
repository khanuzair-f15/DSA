class Solution {
public:
    vector<int> sortedSquares(vector<int>& nums) {

        int i = 0, j = nums.size() - 1;
        // -4 -1 0 3 10
        //
        vector<int> v;
        while (i <= j) {
            if (nums[i] * nums[i] <= nums[j] * nums[j]) {
                v.insert(v.begin(), nums[j] * nums[j]);
                j--;
            } else if (nums[i] * nums[i] > nums[j] * nums[j]) {
                v.insert(v.begin(), nums[i] * nums[i]);
                i++;
            }
        }
        return v;
    }
};