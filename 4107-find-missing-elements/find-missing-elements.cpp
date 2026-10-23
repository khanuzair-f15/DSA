class Solution {
public:
    vector<int> findMissingElements(vector<int>& nums) {

        unordered_set<int> s;
        vector<int> v;
        int min_val = INT_MAX;
        int max_val = INT_MIN;

        for (int i = 0; i < nums.size(); i++) {
            s.insert(nums[i]);
            min_val = std::min(min_val, nums[i]);
            max_val = std::max(max_val, nums[i]);
        }

        for (int i = min_val; i <= max_val; i++) {
            if (s.find(i) == s.end()) {
                v.push_back(i);
            }
        }

        return v;
    }
};