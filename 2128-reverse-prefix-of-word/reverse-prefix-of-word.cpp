class Solution {
public:
    string reversePrefix(string word, char ch) {
        int i = 0;
        for (i = 0; i < word.size(); i++) {
            if (word[i] == ch) {
                break;
            }
        }
        if (i == word.size()) {
            cout << i << word.size() << endl;
            return word;
        } else {
            cout << i << word.size() << endl;
            reverse(word.begin(), word.begin() + i + 1);
            return word;
        }
    }
};