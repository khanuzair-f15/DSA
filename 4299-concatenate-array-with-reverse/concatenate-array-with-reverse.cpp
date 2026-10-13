class Solution {
public:
    vector<int> concatWithReverse(vector<int>& nums) {

        vector<int> v;
        // 1 2 3 3 2 1
        //
        int k = 0;
        for (int i = 0; i < 2 * nums.size(); i++) {
            if (i < nums.size()) {
                v.push_back(nums[i]);
            } else {
                v.push_back(nums[nums.size() - 1 - k]);
                k++;
            }
        }
        return v;
    }
};