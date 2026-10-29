class Solution {
public:
    bool palindrome(string& s) {
        int i = 0;
        int j = s.size() - 1;
        while (i < j) {
            if (s[i] == s[j]) {
                i++;
                j--;
            } else {
                return false;
            }
        }
        return true;
    }
    string firstPalindrome(vector<string>& words) {
        for (auto word : words) {
            if (palindrome(word)) {
                return word;
            }
        }
        return "";
    }
};