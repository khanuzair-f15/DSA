class Solution {
public:
    bool isValid(string s) {
        vector<char> v;

        for (auto i : s) {
            if (i == '(' || i == '{' || i == '[') {
                v.push_back(i);
            } else if (i == ')' || i == '}' || i == ']') {
                if (v.empty())
                    return false;
                if (i == ')' && v.back() == '(') {
                    v.pop_back();
                } else if (i == '}' && v.back() == '{') {
                    v.pop_back();
                } else if (i == ']' && v.back() == '[') {
                    v.pop_back();
                } else {
                    return false;
                }
            }
        }
        if (v.size() != 0) {
            return false;
        }
        return true;
    }
};