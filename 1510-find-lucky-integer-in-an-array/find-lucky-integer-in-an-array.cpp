class Solution {
public:
    int findLucky(vector<int>& arr) {
        unordered_map<int, int> mp;
        for (auto num : arr) {
            mp[num]++;
        }
        int ans = -1;
        for (auto i : mp) {
            if (i.first == i.second) {
                ans = max(i.first, ans);
            }
        }
        return ans;
    }
};