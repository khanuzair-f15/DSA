class Solution {
public:
    vector<int> getSneakyNumbers(vector<int>& nums) {
        set<int> s;
        vector<int> v;
        for (auto i : nums) {
            if (s.count(i)) {
                v.push_back(i);
                continue;
            } else {
                s.insert(i);
            }
        }
        return v;
    }
};