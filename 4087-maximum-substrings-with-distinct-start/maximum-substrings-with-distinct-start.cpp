class Solution {
public:
    int maxDistinct(string s) {
        unordered_set<char> c;
        int ans = 0;
        for (int i = 0; i < s.size(); i++) {
            if (c.count(s[i])) {
                continue;
            } else {
                c.insert(s[i]);
                ans++;
            }
        }
        return ans;
    }
};