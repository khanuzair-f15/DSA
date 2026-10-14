class Solution {
public:
    string reverseVowels(string str) {
        unordered_set<char> s = {'a', 'e', 'i', 'o', 'u',
                                 'A', 'E', 'I', 'O', 'U'};

        int i = 0, j = str.size() - 1;

        while (i < j) {
            if (s.find(str[i]) == s.end()) {
                i++;
            } else if (s.find(str[j]) == s.end()) {
                j--;
            } else if (s.find(str[i]) != s.end() && s.find(str[j]) != s.end()) {
                swap(str[i], str[j]);
                i++;
                j--;
            }
        }
        return str;
    }
};