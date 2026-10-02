class Solution {
public:
    bool uniqueOccurrences(vector<int>& arr) {
        map<int, int> mp;

        for (auto a : arr) {
            mp[a]++;
        }
        for (auto i : mp) {
            cout << i.first << " " << i.second << endl;
        }
        set<int> seen;
        for (auto p : mp) {
            if (seen.count(p.second)) {
                return false;
            }
            seen.insert(p.second);
        }
        return true;
    }
};