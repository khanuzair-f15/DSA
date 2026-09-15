class Solution {
public:
    string longestCommonPrefix(vector<string>& strs) {
        string ans = "";
        sort(strs.begin(), strs.end());
        for (int i = 0; i < min(strs[0].size(), strs.back().size()); i++) {
            if (strs[0][i] == strs.back()[i]) {
                ans += strs[0][i];
            } else {
                break;
            }
        }
        return ans;
    }
};