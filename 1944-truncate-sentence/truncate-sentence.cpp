class Solution {
public:
    string truncateSentence(string s, int k) {

        vector<string> v;
        int count = 0;

        string str = "";
        for (int i = 0; i < s.size(); i++) {

            if (int(s[i]) == 32) {

                v.push_back(str);
                str = "";
                count++;
                continue;
            }
            // k = 5 count k-1
            if (count == k) {
                break;
            }

            str += s[i];
        }
        if (count < k && str != "") {
            v.push_back(str);
        }

        string ans = "";

        for (string s : v) {
            ans += s;
            ans += " ";
        }
        ans.pop_back();
        return ans;
    }
};