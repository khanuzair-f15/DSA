class Solution {
public:
    int firstMatchingIndex(string s) {

        int i = 0;
        int j = s.size() - 1;

        while (i <= j) {
            if (s[i] == s[j]) {
                return i;
            } else {
                i++;
                j--;
            }
        }
        return -1;
    }
};