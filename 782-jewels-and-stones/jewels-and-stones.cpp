class Solution {
public:
    int numJewelsInStones(string jewels, string stones) {
        int ans = 0;
        int arr[52] = {};
        for (char c : stones) {
            if (c >= 'A' && c <= 'Z') {
                arr[c - 'A']++;
            } else if (c >= 'a' && c <= 'z') {
                arr[c - 'a' + 26]++;
            }
        }

        for (char c : jewels) {

            if (c >= 'A' && c <= 'Z') {
                ans += arr[c - 'A'];
            } else if (c >= 'a' && c <= 'z') {
                ans += arr[c - 'a' + 26];
            }
        }
        return ans;
    }
};