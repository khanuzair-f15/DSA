class Solution {
public:
    int singleNumber(vector<int>& nums) {

        unordered_set<int> s;

        for (int i = 0; i < nums.size(); i++) {

            if (s.count(nums[i])) {
                s.erase(nums[i]);
            } else {
                s.insert(nums[i]);
            }
        }
        int x = *s.begin();
        return x;
    }
};