class Solution {
public:
    vector<int> pivotArray(vector<int>& nums, int pivot) {

        vector<int> v;
        vector<int> v2;
        vector<int> v3;
        int k = 0;
        for (int i = 0; i < nums.size(); i++) {

            if (nums[i] == pivot) {
                v3.push_back(nums[i]);
                continue;
            }
            if (nums[i] < pivot) {
                v.push_back(nums[i]);
            } else {
                v2.push_back(nums[i]);
            }
        }
        v.insert(v.end(), v3.begin(), v3.end());
        v.insert(v.end(), v2.begin(), v2.end());
        for (auto i : v) {
            cout << i << " ";
        }
        return v;
    }
};