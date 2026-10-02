class Solution {
public:
    bool uniqueOccurrences(vector<int>& arr) {
        map<int, int> mp;
        for (auto a : arr) {
            mp[a]++;
        }
        unordered_set<int> seen;
        for (auto p : mp) {
            seen.insert(p.second);
        }
        return seen.size() == mp.size();
    }
};