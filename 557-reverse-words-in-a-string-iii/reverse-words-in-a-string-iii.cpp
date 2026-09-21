class Solution {
public:
    string reverseWords(string s) {

        string ans = "";
        string rev = " ";

        for (auto ch : s) {

            rev += ch;

            if (ch == ' ') {
                rev.pop_back();
                reverse(rev.begin(), rev.end());

                ans = ans + rev;
                rev = " ";
            }
        }
        if (!rev.empty()) {

            reverse(rev.begin(), rev.end());
            ans += rev;
        }
        ans.pop_back();
        return ans;
    }
};