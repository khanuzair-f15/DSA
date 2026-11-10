/**
 * Definition for singly-linked list.
 * struct ListNode {
 *     int val;
 *     ListNode *next;
 *     ListNode() : val(0), next(nullptr) {}
 *     ListNode(int x) : val(x), next(nullptr) {}
 *     ListNode(int x, ListNode *next) : val(x), next(next) {}
 * };
 */
class Solution {
public:
    void inserrtNode(ListNode*& root, int data) {
        ListNode* temp = new ListNode(data);
        temp->next = root->next;
        root->next = temp;
    }
    int gcd(int a, int b) {
        // eucledian way to find gcd
        while (b != 0) {
            int remainder = a % b;
            a = b;
            b = remainder;
        }
        return a;
    }
    ListNode* insertGreatestCommonDivisors(ListNode* head) {
        if (head->next == nullptr) {
            return head;
        }
        ListNode* temp = head;
        while (temp->next != nullptr) {
           // int data = gcd(temp->val, temp->next->val);
            inserrtNode(temp, gcd(temp->val, temp->next->val));
            temp = temp->next->next;
        }
        return head;
    }
};