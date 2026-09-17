class Solution {
public:
    vector<int> getSneakyNumbers(vector<int>& nums) {
//Beats 49.05%
        std::ios_base::sync_with_stdio(false);
        std::cin.tie(nullptr);

        unordered_set<int> s;
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