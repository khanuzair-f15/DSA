class Solution {
public:
    vector<int> recoverOrder(vector<int>& order, vector<int>& friends) {

        unordered_set<int> s(friends.begin(), friends.end());

        vector<int> v;

        for (auto a : order) {
            if (s.find(a) != s.end()) {
                v.push_back(a);
            }
        }
        return v;
    }
};